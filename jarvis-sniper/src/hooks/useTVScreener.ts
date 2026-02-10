'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { TVStockData } from '@/lib/tv-screener';
import { getMarketPhase, type MarketPhase } from '@/lib/tv-screener';

/**
 * Polling intervals by market phase (milliseconds).
 *
 * During active market hours we poll every 60 seconds so the UI stays
 * reasonably fresh. When the market is closed we back off to 5 minutes
 * since the data is static anyway.
 */
const POLL_INTERVALS: Record<MarketPhase, number> = {
  PRE_MARKET: 60_000,
  REGULAR: 60_000,
  AFTER_HOURS: 60_000,
  CLOSED: 300_000,
};

export interface UseTVScreenerReturn {
  data: Record<string, TVStockData>;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  marketPhase: MarketPhase;
  refetch: () => Promise<void>;
}

/**
 * React hook that polls `/api/tv-screener` with adaptive intervals based
 * on the current US equity market phase.
 *
 * - Uses `setTimeout` chaining (not `setInterval`) so the interval adapts
 *   dynamically when the market phase changes.
 * - On error the hook sets an error string but keeps stale data -- stale
 *   data is better than empty.
 */
export function useTVScreener(): UseTVScreenerReturn {
  const [data, setData] = useState<Record<string, TVStockData>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [marketPhase, setMarketPhase] = useState<MarketPhase>(getMarketPhase);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/tv-screener');
      if (!res.ok) {
        throw new Error(`TV screener API returned ${res.status}`);
      }

      const json = await res.json();

      if (!json.success) {
        throw new Error(json.error ?? 'TV screener API returned unsuccessful response');
      }

      if (mountedRef.current) {
        setData(json.data ?? {});
        setError(null);
        setLastUpdated(new Date());
        setMarketPhase(getMarketPhase());
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch TV data');
        // Intentionally do NOT clear existing data -- stale is better than empty
        setMarketPhase(getMarketPhase());
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // Polling loop via setTimeout chaining
  useEffect(() => {
    mountedRef.current = true;

    async function poll() {
      await fetchData();

      if (!mountedRef.current) return;

      // Schedule next poll based on current market phase
      const currentPhase = getMarketPhase();
      const interval = POLL_INTERVALS[currentPhase];
      timeoutRef.current = setTimeout(poll, interval);
    }

    // Kick off the first fetch immediately
    poll();

    return () => {
      mountedRef.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [fetchData]);

  const refetch = useCallback(async () => {
    setLoading(true);
    await fetchData();
  }, [fetchData]);

  return { data, loading, error, lastUpdated, marketPhase, refetch };
}
