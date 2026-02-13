import { NextResponse } from 'next/server';
import { graduationCache } from '@/lib/server-cache';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';

// Inline regime/trend helpers (these live in useMacroData.ts with 'use client',
// which cannot be imported in a server route).
type MarketRegime = 'risk_on' | 'risk_off' | 'neutral';
type BtcTrend = 'pumping' | 'dumping' | 'flat';

function determineRegime(btcChange24h: number): MarketRegime {
  if (btcChange24h > 3) return 'risk_on';
  if (btcChange24h < -3) return 'risk_off';
  return 'neutral';
}

function determineBtcTrend(btcChange24h: number): BtcTrend {
  if (btcChange24h > 2) return 'pumping';
  if (btcChange24h < -2) return 'dumping';
  return 'flat';
}

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
const MACRO_STALE_KEY = 'macro:latest:stale';
const MACRO_TTL_MS = 60_000; // 60 seconds
const MACRO_STALE_TTL_MS = 10 * 60_000; // 10 minutes

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

async function fetchJupiterSolPrice(timeoutMs = 6000): Promise<number | null> {
  // Jupiter Lite price API (no key) for SOL mint
  const SOL_MINT = 'So11111111111111111111111111111111111111112';
  const url = `https://lite-api.jup.ag/price/v3?ids=${encodeURIComponent(SOL_MINT)}`;

  try {
    const res = await fetchWithTimeout(url, timeoutMs);
    if (!res.ok) return null;
    const json: any = await res.json().catch(() => null);
    const price = json?.data?.[SOL_MINT]?.price ?? json?.data?.[0]?.price ?? null;
    const n = typeof price === 'number' ? price : Number(price);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  try {
    // Check cache first (cache hits should never be rate-limited).
    const cached = graduationCache.get(MACRO_CACHE_KEY);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
        },
      });
    }

    const stale = graduationCache.get(MACRO_STALE_KEY);
    if (stale) {
      return NextResponse.json({ ...stale, _stale: true }, {
        headers: { 'X-Cache': 'STALE' },
      });
    }

    // Rate limit check (only for upstream refresh attempts)
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
    if (!limit.allowed) {
      // Graceful degradation: avoid 429 breaking UI; return a fallback payload.
      const solPrice = await fetchJupiterSolPrice();
      return NextResponse.json(
        {
          error: 'Rate limit exceeded',
          btcPrice: null,
          btcChange24h: null,
          solPrice,
          solChange24h: null,
          regime: null,
          btcTrend: null,
          timestamp: Date.now(),
          _fallback: true,
          _rateLimited: true,
        },
        {
          status: 200,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    // Fetch from CoinGecko
    const res = await fetchWithTimeout(COINGECKO_URL);
    if (!res.ok) {
      console.warn(`[Macro] CoinGecko returned ${res.status}`);
      // Graceful degradation: return best-effort SOL price via Jupiter Lite.
      const solPrice = await fetchJupiterSolPrice();
      return NextResponse.json(
        {
          error: 'Upstream API error',
          btcPrice: null,
          btcChange24h: null,
          solPrice,
          solChange24h: null,
          regime: null,
          btcTrend: null,
          timestamp: Date.now(),
          _fallback: true,
        },
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
    graduationCache.set(MACRO_STALE_KEY, payload, MACRO_STALE_TTL_MS);

    return NextResponse.json(payload, {
      headers: {
        'X-Cache': 'MISS',
        'X-RateLimit-Remaining': String(limit.remaining),
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120',
      },
    });
  } catch (err) {
    console.error('[Macro] Unexpected error:', err);
    // Graceful degradation: return null data with 200 instead of 500
    // so client-side polling doesn't crash
    const solPrice = await fetchJupiterSolPrice().catch(() => null);
    return NextResponse.json(
      {
        error: 'Internal server error',
        btcPrice: null,
        btcChange24h: null,
        solPrice,
        solChange24h: null,
        regime: null,
        btcTrend: null,
        timestamp: Date.now(),
        _fallback: true,
      },
    );
  }
}
