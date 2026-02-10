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

  useEffect(() => {
    mountedRef.current = true;

    async function fetchMacro() {
      try {
        const res = await fetch('/api/macro');
        if (!res.ok) throw new Error(`macro fetch failed: ${res.status}`);
        const json = await res.json();

        if (!mountedRef.current) return;

        setData({
          btcPrice: json.btcPrice ?? null,
          btcChange24h: json.btcChange24h ?? null,
          solPrice: json.solPrice ?? null,
          solChange24h: json.solChange24h ?? null,
          regime: json.regime ?? null,
          btcTrend: json.btcTrend ?? null,
          loading: false,
        });
      } catch {
        if (!mountedRef.current) return;
        // On error, keep existing data but mark not loading
        setData((prev) => ({ ...prev, loading: false }));
      }
    }

    fetchMacro();
    const interval = setInterval(fetchMacro, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, []);

  return data;
}
