'use client';

import { useState, useEffect, useRef } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MarketRegime = 'risk_on' | 'risk_off' | 'neutral';
export type BtcTrend = 'pumping' | 'dumping' | 'flat';

export interface MacroData {
  btcPrice: number | null;
  btcChange24h: number | null;
  solPrice: number | null;
  solChange24h: number | null;
  regime: MarketRegime | null;
  btcTrend: BtcTrend | null;
  loading: boolean;
}

// ---------------------------------------------------------------------------
// Pure helpers (exported for testing)
// ---------------------------------------------------------------------------

/** Determine overall market regime based on BTC 24h change. */
export function determineRegime(btcChange24h: number): MarketRegime {
  if (btcChange24h > 3) return 'risk_on';
  if (btcChange24h < -3) return 'risk_off';
  return 'neutral';
}

/** Determine BTC short-term trend based on 24h change. */
export function determineBtcTrend(btcChange24h: number): BtcTrend {
  if (btcChange24h > 2) return 'pumping';
  if (btcChange24h < -2) return 'dumping';
  return 'flat';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 60_000; // 60 seconds
const MAX_CONSECUTIVE_ERRORS = 5;
const BASE_BACKOFF_MS = 5_000; // 5s base for exponential backoff

const INITIAL_STATE: MacroData = {
  btcPrice: null,
  btcChange24h: null,
  solPrice: null,
  solChange24h: null,
  regime: null,
  btcTrend: null,
  loading: true,
};

/**
 * Fetches macro market data (BTC/SOL prices, regime, trend) from our
 * server-side `/api/macro` route. Polls every 60 seconds.
 */
export function useMacroData(): MacroData {
  const [data, setData] = useState<MacroData>(INITIAL_STATE);
  const mountedRef = useRef(true);
  const errorCountRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;

    async function fetchMacro() {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10_000); // 10s timeout
        const res = await fetch('/api/macro', { signal: controller.signal });
        clearTimeout(timer);

        if (!res.ok) throw new Error(`macro fetch failed: ${res.status}`);
        const json = await res.json();

        if (!mountedRef.current) return;

        // Reset error count on success
        errorCountRef.current = 0;

        setData({
          btcPrice: json.btcPrice ?? null,
          btcChange24h: json.btcChange24h ?? null,
          solPrice: json.solPrice ?? null,
          solChange24h: json.solChange24h ?? null,
          regime: json.regime ?? null,
          btcTrend: json.btcTrend ?? null,
          loading: false,
        });
      } catch (err) {
        if (!mountedRef.current) return;
        errorCountRef.current += 1;
        console.warn(
          `[useMacroData] Fetch failed (${errorCountRef.current}/${MAX_CONSECUTIVE_ERRORS}):`,
          err instanceof Error ? err.message : err,
        );
        // On error, keep existing data but mark not loading
        setData((prev) => ({ ...prev, loading: false }));
      }

      // Schedule next poll with exponential backoff on consecutive errors
      if (!mountedRef.current) return;
      const backoff = errorCountRef.current > 0
        ? Math.min(BASE_BACKOFF_MS * Math.pow(2, errorCountRef.current - 1), POLL_INTERVAL_MS * 5)
        : POLL_INTERVAL_MS;
      timeoutRef.current = setTimeout(fetchMacro, backoff);
    }

    fetchMacro();

    return () => {
      mountedRef.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, []);

  return data;
}
