import { NextResponse } from 'next/server';
import { isAllowedPerpsMarket, proxyPerpsGet } from '@/lib/perps/proxy';

export const runtime = 'nodejs';

const PYTH_BENCHMARKS_BASE = 'https://benchmarks.pyth.network/v1/shims/tradingview/history';
const MARKET_SYMBOL: Record<string, string> = {
  'SOL-USD': 'Crypto.SOL/USD',
  'BTC-USD': 'Crypto.BTC/USD',
  'ETH-USD': 'Crypto.ETH/USD',
};
const ALLOWED_RESOLUTIONS = new Set(['1', '5', '15', '60']);

function normalizeResolution(raw: string | null): string {
  const value = String(raw || '').trim();
  return ALLOWED_RESOLUTIONS.has(value) ? value : '5';
}

function asNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

async function fallbackHistory(market: string, resolution: string): Promise<NextResponse> {
  const now = Math.floor(Date.now() / 1000);
  const from = now - 86400;
  const symbol = MARKET_SYMBOL[market] ?? `Crypto.${market.replace('-', '/')}`;
  const url = new URL(PYTH_BENCHMARKS_BASE);
  url.searchParams.set('symbol', symbol);
  url.searchParams.set('resolution', resolution);
  url.searchParams.set('from', String(from));
  url.searchParams.set('to', String(now));

  try {
    const upstream = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'User-Agent': String(process.env.PERPS_HTTP_USER_AGENT || 'JarvisPerps/1.0 (+https://kr8tiv.web.app)'),
      },
      cache: 'no-store',
    });

    const payload = await upstream.json().catch(() => ({}));
    const obj = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
    if (!upstream.ok) {
      return NextResponse.json(
        {
          market,
          resolution,
          candles: [],
          error: 'fallback_fetch_failed',
          status: upstream.status,
          reason: String(obj.reason || obj.error || 'upstream_error'),
          source: 'pyth-benchmarks-fallback',
        },
        { status: 502 },
      );
    }

    if (obj.s !== 'ok') {
      return NextResponse.json(
        {
          market,
          resolution,
          candles: [],
          error: String(obj.s || 'no_data'),
          status: null,
          reason: String(obj.s || 'no_data'),
          source: 'pyth-benchmarks-fallback',
        },
        { status: 200 },
      );
    }

    const t = Array.isArray(obj.t) ? obj.t : [];
    const o = Array.isArray(obj.o) ? obj.o : [];
    const h = Array.isArray(obj.h) ? obj.h : [];
    const l = Array.isArray(obj.l) ? obj.l : [];
    const c = Array.isArray(obj.c) ? obj.c : [];
    const candles = t.map((_, i) => ({
      time: asNumber(t[i]),
      open: asNumber(o[i]),
      high: asNumber(h[i]),
      low: asNumber(l[i]),
      close: asNumber(c[i]),
    })).filter((row) => row.time > 0 && row.high >= row.low);

    return NextResponse.json({
      market,
      resolution,
      candles,
      stale: false,
      source: 'pyth-benchmarks-fallback',
    });
  } catch (error) {
    const details = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        market,
        resolution,
        candles: [],
        error: 'fallback_unavailable',
        reason: details,
        source: 'pyth-benchmarks-fallback',
      },
      { status: 502 },
    );
  }
}

export async function GET(
  request: Request,
  context: { params: Promise<{ market: string }> },
) {
  const { market } = await context.params;
  const normalized = String(market || '').trim().toUpperCase();
  if (!isAllowedPerpsMarket(normalized)) {
    return NextResponse.json(
      {
        error: 'Unknown market. Allowed: SOL-USD, BTC-USD, ETH-USD',
      },
      { status: 404 },
    );
  }

  const upstreamResponse = await proxyPerpsGet(`/history/${normalized}`, request);
  if (upstreamResponse.status !== 502) {
    return upstreamResponse;
  }

  const url = new URL(request.url);
  const resolution = normalizeResolution(url.searchParams.get('resolution'));
  return fallbackHistory(normalized, resolution);
}
