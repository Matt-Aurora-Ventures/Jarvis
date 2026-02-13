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

const MAX_CONSECUTIVE_ERRORS = 5;
const BASE_BACKOFF_MS = 10_000;

export interface UseTVScreenerReturn {
  data: Record<string, TVStockData>;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  marketPhase: MarketPhase;
  refetch: () => Promise<void>;
}

function isMarketPhase(value: unknown): value is MarketPhase {
  return (
    value === 'PRE_MARKET'
    || value === 'REGULAR'
    || value === 'AFTER_HOURS'
    || value === 'CLOSED'
  );
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
export function useTVScreener(enabled = true): UseTVScreenerReturn {
  const [data, setData] = useState<Record<string, TVStockData>>({});
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [marketPhase, setMarketPhase] = useState<MarketPhase>(getMarketPhase);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const errorCountRef = useRef(0);

  const fetchData = useCallback(async (): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 15_000); // 15s timeout
      const res = await fetch('/api/tv-screener', { signal: controller.signal });
      clearTimeout(timer);

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
        const timestamp = typeof json.timestamp === 'string' ? new Date(json.timestamp) : new Date();
        setLastUpdated(Number.isFinite(timestamp.getTime()) ? timestamp : new Date());
        setMarketPhase(isMarketPhase(json.marketPhase) ? json.marketPhase : getMarketPhase());
        errorCountRef.current = 0; // Reset on success
      }
      return true;
    } catch (err) {
      if (mountedRef.current) {
        errorCountRef.current = Math.min(errorCountRef.current + 1, MAX_CONSECUTIVE_ERRORS);
        setError(err instanceof Error ? err.message : 'Failed to fetch TV data');
        // Intentionally do NOT clear existing data -- stale is better than empty
        setMarketPhase(getMarketPhase());
        console.warn(
          `[useTVScreener] Fetch failed (${errorCountRef.current}/${MAX_CONSECUTIVE_ERRORS}):`,
          err instanceof Error ? err.message : err,
        );
      }
      return false;
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // Polling loop via setTimeout chaining with exponential backoff on errors
  useEffect(() => {
    if (!enabled) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setLoading(false);
      setError(null);
      setMarketPhase(getMarketPhase());
      return;
    }

    mountedRef.current = true;

    async function poll() {
      await fetchData();

      if (!mountedRef.current) return;

      // Schedule next poll based on current market phase + error backoff
      const currentPhase = getMarketPhase();
      const baseInterval = POLL_INTERVALS[currentPhase];
      const interval = errorCountRef.current > 0
        ? Math.min(BASE_BACKOFF_MS * Math.pow(2, errorCountRef.current - 1), baseInterval * 5)
        : baseInterval;
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
  }, [enabled, fetchData]);

  const refetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    await fetchData();
  }, [enabled, fetchData]);

  return { data, loading, error, lastUpdated, marketPhase, refetch };
}
