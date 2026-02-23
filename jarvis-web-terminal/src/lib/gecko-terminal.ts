'use client';

/**
 * GeckoTerminal API Service for Solana OHLCV Candlestick Data
 *
 * Free API -- no key required -- 30 req/min rate limit.
 * Provides OHLCV candles, trending pools, and new pools on Solana.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GECKO_BASE = 'https://api.geckoterminal.com/api/v2';
const DEXSCREENER_BASE = 'https://api.dexscreener.com/token-pairs/v1/solana';
const REFRESH_INTERVAL_MS = 15_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OHLCVCandle {
  time: number;   // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type TimeInterval = '1m' | '5m' | '15m' | '1h' | '4h' | '1D';

export interface TrendingPool {
  name: string;
  address: string;
  baseToken: { symbol: string; address: string };
  quoteToken: { symbol: string; address: string };
  priceUsd: number;
  priceChange24h: number;
  volume24h: number;
}

export interface NewPool {
  name: string;
  address: string;
  baseToken: { symbol: string; address: string };
  quoteToken: { symbol: string; address: string };
  priceUsd: number;
  priceChange24h: number;
  volume24h: number;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Interval mapping
// ---------------------------------------------------------------------------

interface IntervalConfig {
  timeframe: 'minute' | 'hour' | 'day';
  aggregate: number;
}

const INTERVAL_MAP: Record<TimeInterval, IntervalConfig> = {
  '1m':  { timeframe: 'minute', aggregate: 1 },
  '5m':  { timeframe: 'minute', aggregate: 5 },
  '15m': { timeframe: 'minute', aggregate: 15 },
  '1h':  { timeframe: 'hour',   aggregate: 1 },
  '4h':  { timeframe: 'hour',   aggregate: 4 },
  '1D':  { timeframe: 'day',    aggregate: 1 },
};

// ---------------------------------------------------------------------------
// Pool address cache (DexScreener -> pool address)
// ---------------------------------------------------------------------------

const poolAddressCache = new Map<string, string>();

// ---------------------------------------------------------------------------
// fetchOHLCV
// ---------------------------------------------------------------------------

/**
 * Fetch OHLCV candlestick data for a Solana pool from GeckoTerminal.
 *
 * @param poolAddress - The pool (pair) address on Solana.
 * @param interval    - Candle interval: 1m, 5m, 15m, 1h, 4h, 1D.
 * @param limit       - Number of candles to fetch (max 1000, default 300).
 * @returns Candles sorted ascending by time.
 */
export async function fetchOHLCV(
  poolAddress: string,
  interval: TimeInterval,
  limit: number = 300,
): Promise<OHLCVCandle[]> {
  const config = INTERVAL_MAP[interval];
  if (!config) {
    throw new Error(`Unsupported interval: ${interval}`);
  }

  const { timeframe, aggregate } = config;

  // For daily candles GeckoTerminal ignores the aggregate param
  const aggregateParam = timeframe === 'day' ? '' : `&aggregate=${aggregate}`;

  const url =
    `${GECKO_BASE}/networks/solana/pools/${poolAddress}/ohlcv/${timeframe}` +
    `?limit=${limit}${aggregateParam}&currency=usd`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`GeckoTerminal OHLCV error: ${res.status} ${res.statusText}`);
  }

  const json = await res.json();
  const rawList: Array<[number, string, string, string, string, string]> =
    json?.data?.attributes?.ohlcv_list ?? [];

  // GeckoTerminal returns newest-first; reverse to ascending order
  return rawList
    .map(([ts, o, h, l, c, v]) => ({
      time: ts,
      open: parseFloat(o),
      high: parseFloat(h),
      low: parseFloat(l),
      close: parseFloat(c),
      volume: parseFloat(v),
    }))
    .reverse();
}

// ---------------------------------------------------------------------------
// fetchTrendingPools
// ---------------------------------------------------------------------------

/**
 * Fetch trending Solana pools from GeckoTerminal.
 */
export async function fetchTrendingPools(): Promise<TrendingPool[]> {
  const url = `${GECKO_BASE}/networks/solana/trending_pools?page=1`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`GeckoTerminal trending pools error: ${res.status}`);
  }

  const json = await res.json();
  const pools: unknown[] = json?.data ?? [];

  return pools.map((pool: any) => {
    const attr = pool.attributes ?? {};
    const relationships = pool.relationships ?? {};

    return {
      name: attr.name ?? '',
      address: attr.address ?? pool.id?.split('_')[1] ?? '',
      baseToken: {
        symbol: attr.base_token_symbol ?? '',
        address: relationships?.base_token?.data?.id?.split('_')[1] ?? '',
      },
      quoteToken: {
        symbol: attr.quote_token_symbol ?? '',
        address: relationships?.quote_token?.data?.id?.split('_')[1] ?? '',
      },
      priceUsd: parseFloat(attr.base_token_price_usd ?? '0'),
      priceChange24h: parseFloat(attr.price_change_percentage?.h24 ?? '0'),
      volume24h: parseFloat(attr.volume_usd?.h24 ?? '0'),
    };
  });
}

// ---------------------------------------------------------------------------
// fetchNewPools
// ---------------------------------------------------------------------------

/**
 * Fetch newly created Solana pools from GeckoTerminal.
 */
export async function fetchNewPools(): Promise<NewPool[]> {
  const url = `${GECKO_BASE}/networks/solana/new_pools?page=1`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`GeckoTerminal new pools error: ${res.status}`);
  }

  const json = await res.json();
  const pools: unknown[] = json?.data ?? [];

  return pools.map((pool: any) => {
    const attr = pool.attributes ?? {};
    const relationships = pool.relationships ?? {};

    return {
      name: attr.name ?? '',
      address: attr.address ?? pool.id?.split('_')[1] ?? '',
      baseToken: {
        symbol: attr.base_token_symbol ?? '',
        address: relationships?.base_token?.data?.id?.split('_')[1] ?? '',
      },
      quoteToken: {
        symbol: attr.quote_token_symbol ?? '',
        address: relationships?.quote_token?.data?.id?.split('_')[1] ?? '',
      },
      priceUsd: parseFloat(attr.base_token_price_usd ?? '0'),
      priceChange24h: parseFloat(attr.price_change_percentage?.h24 ?? '0'),
      volume24h: parseFloat(attr.volume_usd?.h24 ?? '0'),
      createdAt: attr.pool_created_at ?? '',
    };
  });
}

// ---------------------------------------------------------------------------
// getPoolAddressFromDexScreener
// ---------------------------------------------------------------------------

/**
 * Resolve a token mint address to the highest-liquidity pool address
 * via the DexScreener API. Results are cached in a module-level Map.
 *
 * @param tokenMint - The Solana token mint address.
 * @returns The pool address or null if not found.
 */
export async function getPoolAddressFromDexScreener(
  tokenMint: string,
): Promise<string | null> {
  // Return cached result if available
  const cached = poolAddressCache.get(tokenMint);
  if (cached !== undefined) {
    return cached;
  }

  try {
    const url = `${DEXSCREENER_BASE}/${tokenMint}`;
    const res = await fetch(url);
    if (!res.ok) {
      console.warn(`DexScreener API error: ${res.status}`);
      return null;
    }

    const pairs: any[] = await res.json();

    if (!Array.isArray(pairs) || pairs.length === 0) {
      return null;
    }

    // Find the pair with the highest liquidity
    let bestPair: any = pairs[0];
    let bestLiquidity = parseFloat(bestPair?.liquidity?.usd ?? '0');

    for (const pair of pairs) {
      const liq = parseFloat(pair?.liquidity?.usd ?? '0');
      if (liq > bestLiquidity) {
        bestLiquidity = liq;
        bestPair = pair;
      }
    }

    const poolAddress: string | null = bestPair?.pairAddress ?? null;

    if (poolAddress) {
      poolAddressCache.set(tokenMint, poolAddress);
    }

    return poolAddress;
  } catch (err) {
    console.error('DexScreener pool lookup failed:', err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// useOHLCV React Hook
// ---------------------------------------------------------------------------

/**
 * React hook for fetching OHLCV candle data with auto-refresh.
 *
 * - Fetches on mount and when poolAddress or interval changes.
 * - Re-fetches every 15 seconds.
 * - Returns empty array when poolAddress is null.
 */
export function useOHLCV(
  poolAddress: string | null,
  interval: TimeInterval,
): {
  candles: OHLCVCandle[];
  isLoading: boolean;
  error: string | null;
} {
  const [candles, setCandles] = useState<OHLCVCandle[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const doFetch = useCallback(async () => {
    if (!poolAddress) {
      setCandles([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);

    try {
      const data = await fetchOHLCV(poolAddress, interval);
      setCandles(() => data);
      setError(() => null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch OHLCV data';
      setError(() => message);
      // Keep stale candles on error so the chart stays visible
    } finally {
      setIsLoading(false);
    }
  }, [poolAddress, interval]);

  useEffect(() => {
    // Initial fetch
    doFetch();

    // Set up 15-second refresh interval
    intervalRef.current = setInterval(doFetch, REFRESH_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [doFetch]);

  return { candles, isLoading, error };
}
