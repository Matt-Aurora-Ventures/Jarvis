'use client';

/**
 * xStocks DexScreener API Client
 *
 * Fetches live price data for tokenized equities (xStocks, PreStocks, Indexes)
 * from DexScreener's Solana token endpoint. Batches requests in groups of 30
 * (DexScreener limit) and merges results into a single Map.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ALL_TOKENIZED_EQUITIES } from '@/lib/xstocks-data';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DexPairData {
  /** USD price string from DexScreener */
  priceUsd: string;
  /** 24-hour price change percentage */
  priceChange24h: number;
  /** 24-hour volume in USD */
  volume24h: number;
  /** Fully diluted valuation */
  fdv: number;
  /** Liquidity in USD */
  liquidityUsd: number;
  /** Base token mint address */
  baseTokenAddress: string;
  /** DEX identifier */
  dexId: string;
  /** Pair URL on DexScreener */
  url: string;
}

export interface XStocksPriceMap {
  /** Map of mintAddress -> best DexPairData (highest liquidity pair) */
  prices: Map<string, DexPairData>;
}

export interface UseXStocksDataReturn {
  data: Map<string, DexPairData>;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refetch: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEXSCREENER_BASE = 'https://api.dexscreener.com/tokens/v1/solana';
const BATCH_SIZE = 30;
const REFRESH_INTERVAL_MS = 60_000; // 60 seconds

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Splits an array into chunks of a given size.
 */
function chunkArray<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

/**
 * Parse a single DexScreener pair object into our DexPairData shape.
 * DexScreener returns pairs where baseToken.address matches our mint.
 */
function parsePair(pair: Record<string, unknown>): DexPairData | null {
  try {
    const baseToken = pair.baseToken as Record<string, string> | undefined;
    if (!baseToken?.address) return null;

    const priceChange = pair.priceChange as Record<string, number> | undefined;
    const volume = pair.volume as Record<string, number> | undefined;
    const liquidity = pair.liquidity as Record<string, number> | undefined;

    return {
      priceUsd: (pair.priceUsd as string) ?? '0',
      priceChange24h: priceChange?.h24 ?? 0,
      volume24h: volume?.h24 ?? 0,
      fdv: (pair.fdv as number) ?? 0,
      liquidityUsd: liquidity?.usd ?? 0,
      baseTokenAddress: baseToken.address,
      dexId: (pair.dexId as string) ?? '',
      url: (pair.url as string) ?? '',
    };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Core fetch function
// ---------------------------------------------------------------------------

/**
 * Fetch price data for all tokenized equities from DexScreener.
 * Batches addresses into groups of 30 and fetches in parallel.
 */
export async function fetchAllXStocksPrices(): Promise<Map<string, DexPairData>> {
  const allMints = ALL_TOKENIZED_EQUITIES.map((eq) => eq.mintAddress);
  const batches = chunkArray(allMints, BATCH_SIZE);

  const results = await Promise.all(
    batches.map(async (batch) => {
      const addresses = batch.join(',');
      const url = `${DEXSCREENER_BASE}/${addresses}`;

      try {
        const response = await fetch(url, {
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        });

        if (!response.ok) {
          console.warn(
            `[xstocks-api] DexScreener batch failed: ${response.status} ${response.statusText}`
          );
          return new Map<string, DexPairData>();
        }

        const rawData: unknown[] = await response.json();

        // DexScreener returns an array of pair objects
        const pairArray = Array.isArray(rawData) ? rawData : [];

        // Group by base token address, keep the pair with highest liquidity
        const bestByMint = new Map<string, DexPairData>();

        for (const raw of pairArray) {
          const parsed = parsePair(raw as Record<string, unknown>);
          if (!parsed) continue;

          const existing = bestByMint.get(parsed.baseTokenAddress);
          if (!existing || parsed.liquidityUsd > existing.liquidityUsd) {
            bestByMint.set(parsed.baseTokenAddress, parsed);
          }
        }

        return bestByMint;
      } catch (err) {
        console.warn('[xstocks-api] DexScreener batch error:', err);
        return new Map<string, DexPairData>();
      }
    })
  );

  // Merge all batch results into a single Map
  const merged = new Map<string, DexPairData>();
  for (const batchMap of results) {
    for (const [key, value] of batchMap) {
      merged.set(key, value);
    }
  }

  return merged;
}

// ---------------------------------------------------------------------------
// React Hook
// ---------------------------------------------------------------------------

/**
 * Hook: useXStocksData
 *
 * Fetches live xStocks price data on mount and re-fetches every 60 seconds.
 * Uses functional setState for stable callbacks. Returns loading/error state.
 */
export function useXStocksData(): UseXStocksDataReturn {
  const [data, setData] = useState<Map<string, DexPairData>>(() => new Map());
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const result = await fetchAllXStocksPrices();

      setData((prev) => {
        // Only update if we actually got data (don't wipe on empty error response)
        if (result.size === 0 && prev.size > 0) return prev;
        return result;
      });

      setLastUpdated(new Date());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch xStocks data';
      setError(message);
      console.error('[useXStocksData]', message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refetch = useCallback(() => {
    setIsLoading(true);
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchData();

    intervalRef.current = setInterval(fetchData, REFRESH_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchData]);

  return { data, isLoading, error, lastUpdated, refetch };
}
